# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.currency — a tool installed from OUR fork rather than an upstream release.

graphify was forked 2026-08-24 (Ray) to carry upstream PR #2981's `openai-cli`
backend, which is open and unmerged. The fork exposed a blind spot that every
version-reasoning check shared, and these cases pin both halves of it.

THE BLIND SPOT, stated because it is the reason for every test here: a fork can
ship the SAME package name and the SAME version string as the release it sits on.
graphify's does — `graphifyy`, `0.9.48`, and `graphify --version` prints `0.9.48`
either way. Worse, `uv add` leaves the `[project] dependencies` line reading
`graphifyy[all]==0.9.48` and redirects the install from a `[tool.uv.sources]`
table far below it. So the dependency list, the package name, the version string
and the binary's own `--version` ALL still say "upstream 0.9.48" while the bytes
come from a fork. Only `[tool.uv.sources].rev` says otherwise.

Two consequences, one per direction, and the engine must get both right:

* the ref-vs-version comparison can never succeed against a fork's branch ref, so
  leaving it in place reports permanent FALSE drift on a pin that is exactly
  right — the failure `tag_prefix` already records from #245, where a reader
  learns to ignore a row and then misses the real one;
* the substitute must be STRONGER, not a silencing. It is: the manifest's 40-hex
  commit must equal the SHA pyproject actually installs from, an exact identity
  between the two halves of one pin rather than a version they would both round
  off.

And `tracks = "fork_base"` covers the third thing a fork breaks: bindings that
record a review performed AGAINST a specific upstream release are statements
about the past, digested into authorization ledgers. Dragging them onto the fork
head would re-authorize runs nobody re-approved.
"""

from pathlib import Path

import pytest
from kb_setup.currency import config, sync

_FORK_SHA = "1" * 40
_BASE_SHA = "b" * 40
_FORK_REF = "kb-pin/openai-cli-backend"
_FORK_BLOCK = (
    "[tool.graphify.fork]\n"
    'upstream = "Graphify-Labs/graphify"\n'
    'base_ref = "v0.9.48"\n'
    f'base_commit = "{_BASE_SHA}"\n'
    'reason = "upstream has no codex backend"\n'
    'clears_when = "#2981 merges and ships to PyPI"\n'
)


def _repo(
    tmp_path: Path,
    *,
    fork: str = _FORK_BLOCK,
    bindings: str = "",
    pyproject: str = "",
    manifest_commit: str = _FORK_SHA,
) -> config.ToolSpec:
    (tmp_path / "mise.toml").write_text(
        '[tools]\n"pipx:graphifyy" = { version = "0.9.48" }\n', encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        pyproject
        or (
            "[project]\n"
            'name = "demo"\n'
            'dependencies = ["graphifyy[all]==0.9.48"]\n'
            "\n[tool.uv.sources]\n"
            'graphifyy = { git = "https://github.com/ray-manaloto/graphify",'
            f' rev = "{_FORK_SHA}" }}\n'
        ),
        encoding="utf-8",
    )
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "graphify.manifest").write_text(
        f"url = https://github.com/ray-manaloto/graphify\n"
        f"ref = {_FORK_REF}\n"
        f"commit = {manifest_commit}\n"
        "kind = code\n",
        encoding="utf-8",
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        # `python_package`, NOT `mise_key`: the real spec uses exactly one
        # dependency owner and the loader refuses both. Setting both here is
        # what the first draft of this fixture did, and every case failed on
        # that instead of on what it meant to test.
        'python_package = "graphifyy"\n'
        'binary = "graphify"\n'
        'manifest = "sources/graphify.manifest"\n'
        f"{fork}"
        f"{bindings}",
        encoding="utf-8",
    )
    return config.load(tmp_path)[0]


# ── the config contract ────────────────────────────────────────────────────


def test_a_fork_must_state_why_it_exists_and_what_clears_it(tmp_path: Path) -> None:
    """A fork with no stated exit is how a temporary pin becomes permanent."""
    for omit in ("reason", "clears_when", "upstream", "base_ref", "base_commit"):
        block = "\n".join(
            line for line in _FORK_BLOCK.splitlines() if not line.startswith(f"{omit} =")
        )
        with pytest.raises(ValueError, match="missing required field"):
            _repo(tmp_path, fork=block + "\n")


def test_an_unrecognised_tracks_value_is_refused_not_defaulted(tmp_path: Path) -> None:
    """Falling through to `manifest` would silently drag history onto the fork."""
    with pytest.raises(ValueError, match="tracks must be one of"):
        _repo(
            tmp_path,
            bindings=(
                "\n[[tool.graphify.ref_binding]]\n"
                'path = "x.py"\n'
                'pattern = \'REF = "([^"]+)"\'\n'
                'field = "ref"\n'
                'tracks = "upstream"\n'
            ),
        )


def test_an_unforked_tool_has_no_fork_spec(tmp_path: Path) -> None:
    """The overwhelming majority. Forks must cost nothing to tools that have none."""
    spec = _repo(tmp_path, fork="")
    assert spec.fork is None


# ── the manifest check under a fork ────────────────────────────────────────


def test_a_matching_fork_pin_does_not_report_version_drift(tmp_path: Path) -> None:
    """THE FALSE-DRIFT CASE. A branch ref can never equal an installed version.

    Without the fork branch this returns DRIFT forever on a pin that is exactly
    right, because it compares `kb-pin/openai-cli-backend` against `0.9.48`.
    """
    spec = _repo(tmp_path)
    finding = sync._check_manifest(tmp_path, spec, "0.9.48")
    assert finding.status is not sync.DRIFT, finding.detail


def test_a_fork_declared_but_not_installed_is_drift(tmp_path: Path) -> None:
    """The substitute must be a real check, not a way to stop asking.

    A `[tool.<name>.fork]` block beside a plain PyPI pin is the split this whole
    branch exists to catch: the config claims a fork, the install is upstream.
    """
    spec = _repo(
        tmp_path,
        pyproject='[project]\nname = "demo"\ndependencies = ["graphifyy[all]==0.9.48"]\n',
    )
    finding = sync._check_manifest(tmp_path, spec, "0.9.48")
    assert finding.status is sync.DRIFT
    assert "declared and not used" in finding.detail


def test_the_two_halves_of_one_fork_pin_separating_is_drift(tmp_path: Path) -> None:
    """`sources/*.manifest` and `pyproject.toml` are ONE pin in two files.

    They are edited by different tools — `uv add` writes one, a human writes the
    other — so a rebase that moves only one is the realistic failure.
    """
    spec = _repo(tmp_path, manifest_commit="c" * 40)
    finding = sync._check_manifest(tmp_path, spec, "0.9.48")
    assert finding.status is sync.DRIFT
    assert "separated" in finding.detail


def test_a_pep508_direct_reference_is_also_accepted(tmp_path: Path) -> None:
    """Both idioms are legitimate; uv chose `[tool.uv.sources]`, pip users do not."""
    spec = _repo(
        tmp_path,
        pyproject=(
            "[project]\n"
            'name = "demo"\n'
            "dependencies = ["
            f'"graphifyy[all] @ git+https://github.com/ray-manaloto/graphify@{_FORK_SHA}"'
            "]\n"
        ),
    )
    finding = sync._check_manifest(tmp_path, spec, "0.9.48")
    assert finding.status is not sync.DRIFT, finding.detail


def test_another_packages_git_pin_is_not_mistaken_for_this_ones(tmp_path: Path) -> None:
    """`pyproject.toml` already carries a second git dependency (`skillopt`).

    A regex over the whole file would happily return ITS sha and report a
    confident mismatch about the one thing this check exists to confirm.
    """
    spec = _repo(
        tmp_path,
        pyproject=(
            "[project]\n"
            'name = "demo"\n'
            'dependencies = ["graphifyy[all]==0.9.48"]\n'
            "\n[tool.uv.sources]\n"
            f'skillopt = {{ git = "https://github.com/microsoft/SkillOpt", rev = "{_BASE_SHA}" }}\n'
        ),
    )
    finding = sync._check_manifest(tmp_path, spec, "0.9.48")
    assert finding.status is sync.DRIFT
    assert "declared and not used" in finding.detail, finding.detail


# ── ref bindings under a fork ──────────────────────────────────────────────


def _binding(tmp_path: Path, value: str, *, tracks: str) -> sync.Finding:
    (tmp_path / "x.py").write_text(f'REF = "{value}"\n', encoding="utf-8")
    spec = _repo(
        tmp_path,
        bindings=(
            "\n[[tool.graphify.ref_binding]]\n"
            'path = "x.py"\n'
            'pattern = \'REF = "([^"]+)"\'\n'
            'field = "ref"\n'
            f'tracks = "{tracks}"\n'
        ),
    )
    return sync._check_ref_bindings(tmp_path, spec)


def test_a_fork_base_binding_is_measured_against_the_base_not_the_fork(
    tmp_path: Path,
) -> None:
    """A snapshot identity records what a COMPLETED run was performed against.

    The semantic-corpus constants are digested into authorization ledgers, so
    moving them to the fork head silently re-authorizes runs nobody re-approved
    (`the-graphify-circle-is-mechanical`). Holding at the base is the correct
    answer, not a lenient one.
    """
    assert _binding(tmp_path, "v0.9.48", tracks="fork_base").status is sync.OK


def test_a_fork_base_binding_left_on_an_older_release_is_still_drift(
    tmp_path: Path,
) -> None:
    """Holding at the base is not the same as not being checked.

    This is the direction that matters: `fork_base` must not become a way for a
    stale constant to stop being noticed, which is the SKIP-over-real-drift shape
    this engine refuses everywhere.
    """
    finding = _binding(tmp_path, "v0.9.42", tracks="fork_base")
    assert finding.status is sync.DRIFT
    assert "the fork base" in finding.detail, finding.detail


def test_a_manifest_tracking_binding_still_follows_the_fork(tmp_path: Path) -> None:
    """The default is unchanged: "the revision we RUN" goes where the manifest goes."""
    assert _binding(tmp_path, _FORK_REF, tracks="manifest").status is sync.OK
    assert _binding(tmp_path, "v0.9.48", tracks="manifest").status is sync.DRIFT
