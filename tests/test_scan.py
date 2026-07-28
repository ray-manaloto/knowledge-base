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
_REPO = Path(__file__).parent.parent.absolute()


@pytest.fixture(autouse=True)
def gitleaks_config(tmp_path: Path) -> Path:
    """Give the fixture repo THIS repo's real `.gitleaks.toml`.

    A copy, not a minimal stand-in: the allowlist is the part most likely to
    silently widen, and a test against a config nobody ships would pass while
    the shipped one looked away. `test_gitleaks_scope.py` asserts the config's
    contents; this exercises it.
    """
    target = tmp_path / ".gitleaks.toml"
    target.write_text((_REPO / ".gitleaks.toml").read_text(encoding="utf-8"), encoding="utf-8")
    return target


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
    """Scan the WORKING TREE, the way hk's file-list-driven step effectively does."""
    proc = subprocess.run(
        [
            "gitleaks",
            "dir",
            str(repo_root),
            "--config",
            str(Path(__file__).parent.parent / ".gitleaks.toml"),
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
    assert cmd[cmd.index("--log-opts") + 1] == "deadbeef..HEAD"
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
