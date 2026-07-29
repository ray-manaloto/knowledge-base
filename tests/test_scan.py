"""The range scan must see what the working-tree scan cannot.

This is #67's gate, and the ONE test that matters is the discrimination pair:
plant a secret in a commit, revert it in the next, and confirm the range scan
fires while a scan of the resulting tree stays green. Either half alone proves
nothing — a scan that always fires and a scan that never fires both "pass" a
one-armed test (`probes-need-a-control-arm.md`).

Real git and a real gitleaks, deliberately. The behaviour under test is
gitleaks' own `--log-opts` handling and git's range semantics; a stubbed
subprocess could only confirm the stub, and the sibling `test_gitleaks_scope.py`
already covers the half that IS a config assertion.

`gitleaks` is pinned in `mise.toml`, so it is not allowed to be missing here and
these tests do not skip when it is. A pinned binary that is absent on a host
where it should be present is DRIFT, not a skip — the same call the currency
engine makes.
"""

from __future__ import annotations

import secrets
import string
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from kb_setup import scan

_GITLEAKS_TIMEOUT = 120


def _synthetic_token() -> str:
    """Return a fresh, high-entropy string shaped like a GitHub PAT.

    RANDOM, not a fixed literal, for two independent reasons:

    * gitleaks' default rules apply an ENTROPY threshold, so a low-entropy
      fixture like ``ghp_AAAABBBBCCCC…`` is never flagged and a probe using one
      can only ever report "no leaks" — a test that cannot fail;
    * a literal committed here would itself be a secret-shaped string in a
      tracked file, which is precisely what this module exists to catch.
    """
    alphabet = string.ascii_letters + string.digits
    return "ghp_" + "".join(secrets.choice(alphabet) for _ in range(36))


@pytest.fixture
def planted(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> Callable[[], str]:
    """Return `planted() -> token`: commit a secret, then commit its removal.

    The realistic break, not a convenient one. `verify-before-advancing.md`
    demands the FAIL direction be reintroduced the way it would really happen,
    and the way a secret really survives into a pushed branch is exactly this:
    someone commits it, notices, and removes it in a follow-up commit — leaving
    a clean tree and a dirty history.
    """

    def plant() -> str:
        token = _synthetic_token()
        commit_file("notes/leak.md", f'token = "{token}"\n')
        git("rm", "-q", "--", "notes/leak.md")
        git("commit", "-q", "-m", "remove the note")
        return token

    return plant


def _gitleaks_dir(repo_root: Path) -> int:
    """Scan the WORKING TREE — the question hk's `gitleaks` step asks, not its form.

    NOT equivalent to that step, and the docstring used to imply it was: hk
    passes N file arguments, and `gitleaks dir` IGNORES its path arguments once
    there is more than one (measured last round: 1 arg → 5.01 KB, 2 args →
    8.62 MB). What this shares with the hk step is the SUBJECT — the checked-out
    tree — which is all this control arm needs. The genuine end-to-end arm
    against the real hk step was run by hand and is recorded in `98899e4`.
    (Standards lane, round 1.)
    """
    proc = subprocess.run(
        [
            "gitleaks",
            "dir",
            str(repo_root),
            "--config",
            str(scan.config_path(Path(__file__).parent.parent)),
            "--redact",
            "--no-banner",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=_GITLEAKS_TIMEOUT,
    )
    return proc.returncode


def test_range_scan_catches_a_planted_then_reverted_secret(
    tmp_path: Path, planted: Callable[[], str]
) -> None:
    """THE FAIL ARM — the gate must fire on a secret no tree scan can see."""
    planted()
    ok, summary = scan.scan_range(tmp_path)
    assert not ok, summary
    assert "SECRETS FOUND" in summary


def test_the_working_tree_scan_stays_green_on_the_same_branch(
    tmp_path: Path, planted: Callable[[], str]
) -> None:
    """THE CONTROL ARM — and the whole justification for the gate existing.

    If this failed, the tree scan already covered the case and #67 would be
    imaginary. It passes, which is the measurement: `gitleaks dir` over the
    resulting checkout reports clean while the range above reports a leak.
    """
    planted()
    assert _gitleaks_dir(tmp_path) == 0


def test_a_clean_branch_passes(tmp_path: Path, commit_file: Callable[..., str]) -> None:
    """The PASS arm. Without it every assertion above holds for a gate wired to fail."""
    commit_file("docs/ordinary.md", "nothing to see\n")
    ok, summary = scan.scan_range(tmp_path)
    assert ok, summary
    assert "no secrets" in summary


def test_a_secret_still_present_in_the_tree_is_also_caught(
    tmp_path: Path, commit_file: Callable[..., str]
) -> None:
    """The range scan is a SUPERSET of the tree scan, not a replacement for it.

    Worth pinning: were it only ever able to see deleted blobs, dropping the hk
    step would look harmless. It is not — both run.
    """
    commit_file("notes/live.md", f'token = "{_synthetic_token()}"\n')
    ok, _ = scan.scan_range(tmp_path)
    assert not ok


def test_an_empty_range_passes_and_says_so(tmp_path: Path, git: Callable[..., str]) -> None:
    """A branch with no commits of its own is a genuine pass, not a refusal.

    And it must SAY it scanned nothing: "0 commits scanned" and "0 findings"
    are different sentences, and a summary that blurred them would let an
    unresolved base read as a clean branch.
    """
    git("checkout", "-q", "main")
    git("checkout", "-q", "-b", "empty")
    ok, summary = scan.scan_range(tmp_path)
    assert ok
    assert "nothing to scan" in summary


def test_an_unresolvable_base_fails_closed(tmp_path: Path, commit_file: Callable[..., str]) -> None:
    """A "could not ask" is not a "nothing is wrong".

    The gate's whole value is that a green result means someone looked. A base
    that does not resolve means nobody did, so it must refuse rather than pass.
    """
    commit_file("docs/ordinary.md", "x\n")
    ok, summary = scan.scan_range(tmp_path, base="no-such-ref")
    assert not ok
    assert "could not resolve" in summary


def test_the_base_is_the_merge_base_not_the_ref(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """Three-dot semantics: the question is what the BRANCH added.

    If `main` moves ahead after the branch forks, the range must still be the
    branch's own commits. Resolving to `main` itself would make the range empty
    (or, worse, negative) and silently scan nothing.
    """
    fork = git("rev-parse", "HEAD")
    commit_file("docs/branch-work.md", "x\n")
    git("checkout", "-q", "main")
    commit_file("docs/main-work.md", "x\n")
    git("checkout", "-q", "work")

    assert scan.range_base(tmp_path) == fork
    assert scan.commits_in_range(tmp_path, fork) == 1


def test_a_missing_config_is_reported_as_a_missing_config(
    tmp_path: Path, commit_file: Callable[..., str], gitleaks_config: Path
) -> None:
    """The defect this module's own test suite found, pinned.

    gitleaks fatals with rc=1 on an unloadable config — the SAME code its
    default `--exit-code` uses for findings. The first version of this gate read
    that as `SECRETS FOUND` and accused a clean branch. Both halves of the fix
    are asserted: `--exit-code 2` separates the two codes, and this precheck
    names the cause.
    """
    commit_file("docs/ordinary.md", "x\n")
    gitleaks_config.unlink()
    ok, summary = scan.scan_range(tmp_path)
    assert not ok
    assert "no gitleaks config" in summary
    assert "SECRETS FOUND" not in summary


def test_the_findings_exit_code_is_moved_off_the_error_code() -> None:
    """CONTROL ARM for the test above — 2, and not gitleaks' overloaded default 1.

    Without this, `_LEAKS` could drift back to 1 and every other test here would
    still pass: a leak would be detected, just for a reason that also fires on a
    broken config.
    """
    assert scan._LEAKS == 2
    assert scan._CLEAN == 0


def test_the_config_is_pinned_and_the_secret_is_redacted(tmp_path: Path) -> None:
    """The invocation's non-obvious flags, asserted rather than trusted.

    `--config` because an ambient `GITLEAKS_CONFIG` from another repo must not
    decide what this gate scans (measured: `--config` outranks the env var, the
    reverse of what this round's handoff claimed). `--redact` because a gate
    that prints the credential it found writes it into the session transcript on
    disk — one of the two ways the tokens behind #67 were exposed in the first
    place. `--exit-code` because gitleaks' default overloads rc=1.
    """
    cmd = scan._gitleaks_cmd(tmp_path, "deadbeef")
    assert "--redact" in cmd
    assert cmd[cmd.index("--config") + 1] == str(tmp_path / ".gitleaks.toml")
    assert cmd[cmd.index("--log-opts") + 1].startswith("deadbeef..HEAD")
    assert cmd[cmd.index("--exit-code") + 1] == "2"


def test_the_gate_is_wired_into_ship() -> None:
    """A module nothing calls is not a gate.

    `mise-tasks-only.md` and `ci-local-parity.md` rule 1 both say the same
    thing: a check that is not in the list `ship` enforces gates nothing. This
    is the wiring assertion that keeps the two from drifting apart.
    """
    from kb_setup import pr

    assert "kb-scan-range" in pr.GATES
    assert pr.GATES[0] == "kb-scan-range", "the cheapest, most consequential gate runs first"


def test_a_failed_git_log_is_not_reported_as_clean(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """THE ROUND-1 BLOCKER. gitleaks exits 0 after its own `git log -p` fails.

    It logs the error, reports "0 commits scanned … no leaks found", and returns
    0 — so mapping rc=0 to "no secrets" turned any machine-local git
    misconfiguration into a permanently green, permanently blind gate. That is
    the "could not ask is not nothing is wrong" collapse this module's docstring
    claims immunity to, and it had exactly one arm where it was false.

    The break is realistic and NOT contrived: a `.gitattributes` `diff=` driver
    whose `textconv` command is missing. The attribute must be live across the
    WHOLE range — a first attempt that added it in a later commit did not fire
    and read as a refutation of the finding.
    """
    (tmp_path / ".gitattributes").write_text("*.md diff=broken\n", encoding="utf-8")
    git("add", "--", ".gitattributes")
    git("commit", "-q", "-m", "attrs")
    git("checkout", "-q", "main")
    git("merge", "-q", "--ff-only", "work")
    git("checkout", "-q", "work")
    commit_file("notes/leak.md", f'token = "{_synthetic_token()}"\n')
    git("config", "diff.broken.textconv", "/nonexistent/command")

    ok, summary = scan.scan_range(tmp_path)
    assert not ok, summary
    assert "reported an error" in summary
    assert "no secrets" not in summary


def test_a_deletion_only_range_still_passes(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """CONTROL ARM for the blocker fix, and the reason it matches ERRORS not COUNTS.

    The reviewer who found the blocker proposed comparing gitleaks' own
    "N commits scanned" against the range size. Measured: a legitimate branch
    that ONLY DELETES files also reports `0 commits scanned` and rc=0, with no
    error line — so that fix would have refused honest work forever. Right
    diagnosis, wrong remedy, and only this third arm separates them.
    """
    commit_file("docs/doomed.md", "x\n")
    git("checkout", "-q", "main")
    git("merge", "-q", "--ff-only", "work")
    git("checkout", "-q", "work")
    git("rm", "-q", "--", "docs/doomed.md")
    git("commit", "-q", "-m", "delete it")

    assert scan.commits_in_range(tmp_path, scan.range_base(tmp_path)) == 1
    ok, summary = scan.scan_range(tmp_path)
    assert ok, summary
    assert "no secrets" in summary


def test_no_color_is_passed_or_the_error_markers_cannot_match() -> None:
    r"""The marker check is useless without it, and would look fine.

    gitleaks colours its log level even when stdout is a pipe, so the raw bytes
    are `\\x1b[31mERR\\x1b[0m` and a plain `" ERR "` match finds nothing — a
    detector that can only ever report "no error", which is the same shape as
    the bug it exists to catch.
    """
    assert "--no-color" in scan._gitleaks_cmd(Path("/x"), "deadbeef")
    assert scan._SCAN_ERROR_MARKERS


def test_the_cutoff_prefers_the_remote_tracking_ref(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """A commit on local `main` that has not reached the remote must be SCANNED.

    `ship` pushes `<sha>:refs/heads/<branch>` — a raw SHA, which carries its
    entire ancestry. So an unpushed commit on local `main` is published by that
    push while sitting BELOW a merge-base taken against local `main`: never
    scanned, and now public. Resolving against `origin/main` moves the cutoff
    back past it. (Cold lane, round 1.)

    The old docstring called the failure direction safe because "a stale local
    main widens the range" — true only when local main is BEHIND. This is the
    other direction, which it did not consider.
    """
    remote = tmp_path.parent / f"{tmp_path.name}-remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(remote)], check=True, timeout=_GITLEAKS_TIMEOUT
    )
    git("remote", "add", "origin", str(remote))
    git("push", "-q", "origin", "main")

    # A commit that exists on LOCAL main only, then a branch forked past it.
    git("checkout", "-q", "main")
    unpushed = commit_file("docs/unpushed.md", "x\n")
    git("checkout", "-q", "-b", "later")
    commit_file("docs/branch.md", "x\n")

    base = scan.range_base(tmp_path)
    assert base != unpushed, "the unpushed commit must be INSIDE the range, not the cutoff"
    reachable = git("rev-list", f"{base}..HEAD").splitlines()
    assert unpushed in reachable, "the unpushed commit would be published unscanned"


def test_unknown_argv_is_rejected(tmp_path: Path, commit_file: Callable[..., str]) -> None:
    """A typo must not silently scan the default and print green.

    `-- --bas main` used to do exactly that — a fail-OPEN in the one module
    whose entire contract is failing closed. (Spec lane, round 1.)
    """
    commit_file("docs/ordinary.md", "x\n")
    assert scan.main(tmp_path, ["--bas", "main"]) == 2
    assert scan.main(tmp_path, ["--base"]) == 2
    assert scan.main(tmp_path, ["--base", "main", "extra"]) == 2
    # CONTROL ARM — the accepted shape still works, or this only proves it rejects.
    assert scan.main(tmp_path, ["--base", "main"]) == 0
    assert scan.main(tmp_path, []) == 0


def test_a_secret_introduced_by_a_merge_commit_is_caught(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """An EVIL MERGE — #67's own scenario surviving #67's own gate.

    `git log -p` emits no patch for a merge commit, so content introduced by the
    merge RESOLUTION (present in neither parent) is scanned by nothing. gitleaks
    logs no error for it either, so round 1's marker check does not fire.
    `--diff-merges=first-parent` is the built-in that closes it.

    The FIRST attempt at this probe did not fire, and that matters more than the
    fix: putting the token on the side branch leaves it in an ordinary commit
    that is itself inside the range, which was already caught. The hole needs a
    conflict resolved by writing the token — content in neither parent.
    Measured: without the flag rc=0 over 3 commits and "no leaks found"; with
    it, rc=2. (Silent-failure lane, round 2.)
    """
    commit_file("conf.md", "shared = 1\n")
    git("checkout", "-q", "main")
    git("merge", "-q", "--ff-only", "work")
    git("checkout", "-q", "-b", "side")
    commit_file("conf.md", "shared = 2\n")
    git("checkout", "-q", "work")
    git("merge", "-q", "--ff-only", "main")
    commit_file("conf.md", "shared = 3\n")

    subprocess.run(
        ["git", "-C", str(tmp_path), "merge", "--no-commit", "side"],
        capture_output=True,
        check=False,
        timeout=_GITLEAKS_TIMEOUT,
    )
    # The resolution introduces a token that exists in NEITHER parent.
    (tmp_path / "conf.md").write_text(
        f'shared = 4\ntoken = "{_synthetic_token()}"\n', encoding="utf-8"
    )
    git("add", "--", "conf.md")
    git("commit", "-q", "-m", "merge side")
    (tmp_path / "conf.md").write_text("shared = 4\n", encoding="utf-8")
    git("commit", "-q", "-am", "remove the token")

    ok, summary = scan.scan_range(tmp_path)
    assert not ok, summary
    assert "SECRETS FOUND" in summary


def test_diff_merges_is_in_the_invocation() -> None:
    """CONTROL ARM — the flag the test above depends on, asserted directly.

    Without it that test could pass for an unrelated reason and the flag could
    be dropped in a refactor with the suite staying green.
    """
    cmd = scan._gitleaks_cmd(Path("/x"), "deadbeef", "cafe")
    assert "--diff-merges=first-parent" in cmd[cmd.index("--log-opts") + 1]
    assert "deadbeef..cafe" in cmd[cmd.index("--log-opts") + 1]


def test_a_broken_origin_ref_refuses_rather_than_narrowing(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """`origin/<base>` EXISTS but merge-base against it fails → refuse.

    The first version's loop fell through to local `<base>`, which NARROWS the
    range — the opposite of this function's whole job. Reproduced by the
    silent-failure lane with an unrelated `origin/main`: it returned local
    `main` and reported "no secrets", leaving all of local `main` unscanned and
    still published by the SHA push. (Silent-failure lane and cold lane, round 2.)
    """
    commit_file("docs/work.md", "x\n")
    # An `origin/main` with a completely unrelated history.
    git("checkout", "-q", "--orphan", "unrelated")
    git("rm", "-q", "-rf", ".")
    (tmp_path / "other.md").write_text("y\n", encoding="utf-8")
    git("add", "--", "other.md")
    git("commit", "-q", "-m", "unrelated root")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("checkout", "-q", "work")

    assert scan.range_base(tmp_path) == ""
    ok, summary = scan.scan_range(tmp_path)
    assert not ok
    assert "could not resolve" in summary


def test_the_cutoff_is_the_oldest_candidate_not_the_first_to_resolve(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """Erring wide has to be STRUCTURAL, not incidental.

    The docstring asserted "errs wide by construction" while the code returned
    whichever ref resolved FIRST — true in the common case, guaranteed in none.
    (Spec lane, round 2.)

    The discriminating fixture is the uncommon-but-real one: local `main`
    BEHIND the remote, with the branch forked from the remote tip — what you get
    from a `git fetch` followed by branching off `origin/main`. There
    `merge-base(origin/main, HEAD)` is NEWER than `merge-base(main, HEAD)`, so
    preferring the remote blindly NARROWS the range.

    The first version of this test used a local-main-ahead fixture, where the
    remote candidate is already the oldest — so `return bases[0]` passed it and
    the test proved nothing. Caught by mutating the code it was written for.
    """
    git("checkout", "-q", "main")
    behind = git("rev-parse", "HEAD")

    # Stand in for a remote that has moved on.
    git("checkout", "-q", "-b", "remote-sim")
    commit_file("docs/remote-a.md", "a\n")
    remote_tip = commit_file("docs/remote-b.md", "b\n")
    git("update-ref", "refs/remotes/origin/main", remote_tip)

    # Local `main` stays behind; the working branch forks from the REMOTE tip.
    git("checkout", "-q", "-b", "forked-from-remote", remote_tip)
    commit_file("docs/branch.md", "c\n")

    assert git("rev-parse", "main") == behind, "local main must be BEHIND for this to discriminate"
    base = scan.range_base(tmp_path)
    assert base == behind, (
        "the OLDER candidate must win; preferring origin/ blindly would cut at "
        f"{remote_tip[:12]} and skip two commits"
    )


def test_a_pinned_sha_ahead_of_head_is_still_scanned(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str]
) -> None:
    """`head` must reach the GITLEAKS COMMAND, not just the summary.

    Round 3 mutation-proved that dropping `head` where `_run_gitleaks` builds the
    command left the whole suite green — and the failure is worse than a miss:
    `span` is composed separately in `scan_range`, so the report keeps saying
    `<base>..<pinned sha>` while gitleaks actually scans `<base>..HEAD`. A gate
    lying in its own summary is harder to catch than one that simply refuses.

    The fixture is the real pre-push race rather than a convenient one: the
    pinned SHA is AHEAD of HEAD (captured, then `git reset --hard HEAD~1`), so a
    scan that resolves `HEAD` for itself cannot see the secret at all.
    (Standards lane, round 3.)
    """
    commit_file("docs/clean.md", "ok\n")
    pushed = commit_file("notes/leak.md", f'token = "{_synthetic_token()}"\n')
    git("reset", "-q", "--hard", "HEAD~1")

    assert git("rev-parse", "HEAD") != pushed, "the fixture must put the sha AHEAD of HEAD"
    ok, summary = scan.scan_range(tmp_path, head=pushed)
    assert not ok, summary
    assert "SECRETS FOUND" in summary

    # CONTROL ARM — the same repo scanned at HEAD is genuinely clean, so the
    # assertion above is about the pinned sha and not about the repo.
    ok, summary = scan.scan_range(tmp_path)
    assert ok, summary


def test_a_dead_git_subprocess_is_not_read_as_a_missing_ref(
    tmp_path: Path, git: Callable[..., str], commit_file: Callable[..., str], monkeypatch
) -> None:
    """A dead probe must not become "the ref is absent", which NARROWS the cutoff.

    `_git` used to map its own exceptions onto rc=1 — which is also git's "no
    such ref" and git's "not an ancestor". Injecting an OSError on the existence
    probe therefore moved the cutoff forward and dropped an unpushed commit
    below it, while `ship` still publishes the whole ancestry.
    (Silent-failure lane, round 3.)
    """
    git("checkout", "-q", "main")
    remote_tip = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", remote_tip)
    commit_file("docs/unpushed.md", "x\n")
    git("checkout", "-q", "-b", "ahead")
    commit_file("docs/branch.md", "y\n")

    real_run = subprocess.run

    # The kwargs are RESTATED rather than `**kwargs`: ruff rejects `Any` there
    # (ANN401) and `ty` rejects `object` against `subprocess.run`'s overloads, and
    # this repo has no inline suppressions. These four are exactly what
    # `scan._git` passes.
    def explode(
        cmd: list[str],
        *,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if "rev-parse" in cmd and any("refs/remotes/origin/" in str(a) for a in cmd):
            msg = "injected"
            raise OSError(msg)
        return real_run(cmd, capture_output=capture_output, text=text, check=check, timeout=timeout)

    monkeypatch.setattr(scan.subprocess, "run", explode)
    assert scan.range_base(tmp_path) == "", "a dead probe must refuse, not fall back"
